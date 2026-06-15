"""Loan-tape cash-securitization template orchestrator — Template 19 (CLO/RMBS).

Build order:
    LoanTape  (asset side: stratified tape → pool cashflow projection)
    Waterfall (liability side: sequential-pay turbo waterfall, OC/IC, reserve)
    Notes     (per-note WAL / IRR / rating proxy)
    QC        (conservation + distribution-logic invariants — see each check)
    ComplianceCheck

There is no cross-sheet patch-back: the asset side is self-contained and the
liability side only ever reads it forward, so a single left-to-right pass
builds the whole workbook acyclically.

This template EXTENDS the structured-credit family rather than duplicating it:
``structured_credit`` keeps the static cumulative-loss tranching and ``npl``
keeps the single-curve collection waterfall; this adds the granular loan-tape
cashflow engine + sequential-pay liability structure neither of them models.

QC philosophy: a securitization waterfall makes the residual certificate the
balancing plug, so a naive "cash in == cash out" identity is VACUOUS (true by
construction — the residual silently absorbs any mis-allocation). The checks
below therefore test the DISTRIBUTION LOGIC against quantities that do not
depend on the plug — sequential subordination, interest bounded by what is due,
no excess-spread / reserve leakage to equity while debt is outstanding — so a
mis-wired waterfall actually fails them. Each check's teeth are noted inline.
"""

from __future__ import annotations

from pathlib import Path

from modelforge.builder import layout
from modelforge.builder.base_workbook import build_base_workbook
from modelforge.builder.sheets import (
    sc_loantape, sc_liability_waterfall, sc_note_analytics,
    compliance as compliance_sheet,
    generic_qc,
)

LT_SHEET = "LoanTape"
WF_SHEET = "Waterfall"
NOTES_SHEET = "Notes"


def build(spec, out_path: Path | str, graph_db_path=None):
    def core_sheets(wb, spec, graph, driver_refs, source_rows):
        periods = spec.horizon.periods
        lag = spec.horizon.recovery_lag_periods
        n = periods + 1

        lt_ws = wb.create_sheet(LT_SHEET)
        lt_refs = sc_loantape.build(lt_ws, spec, driver_refs)

        wf_ws = wb.create_sheet(WF_SHEET)
        wf_refs = sc_liability_waterfall.build(wf_ws, spec, lt_refs, lt_sheet=LT_SHEET)

        notes_ws = wb.create_sheet(NOTES_SHEET)
        sc_note_analytics.build(notes_ws, spec, wf_refs, wf_sheet=WF_SHEET)

        # ── QC sheet ───────────────────────────────────────────────────────
        tol = generic_qc.fmt_tol(spec)
        cols = [layout.year_col(i) for i in range(n)]
        proj = [layout.year_col(i) for i in range(1, n)]
        first = layout.year_col(0)
        last = layout.year_col(periods)
        n_notes = int(wf_refs["n_notes"])
        debt = list(range(n_notes - 1))
        senior = int(wf_refs["senior_idx"])

        def _all(terms):
            return "=IF(AND(" + ",".join(terms) + "),1,0)"

        def lt(col, key):
            return f"'{LT_SHEET}'!${col}${lt_refs[key]}"

        def wf(col, key):
            return f"'{WF_SHEET}'!${col}${wf_refs[key]}"

        def lt_sum(key):
            return f"SUM('{LT_SHEET}'!$E${lt_refs[key]}:${last}${lt_refs[key]})"

        # 1. Pool roll-forward telescopes: BOP[t] == EOP[t-1] (catches column drift).
        c1 = [f"ABS({lt(layout.year_col(i),'pool_bop_row')}"
              f"-{lt(layout.year_col(i-1),'pool_eop_row')})<={tol}" for i in range(1, n)]

        # 2. Scheduled+prepay principal closes the performing pool (= initial − Σdefault).
        #    NON-VACUOUS: tests the amortization + final-sweep against the default
        #    curve; a wrong amort rate / missed sweep breaks it. (Recoveries are
        #    validated separately by #3, so they are deliberately excluded here.)
        c2 = (f"=IF(ABS(({lt_sum('pool_sched_row')}+{lt_sum('pool_prepay_row')})"
              f"-({lt(first,'initial_pool_row')}-{lt_sum('pool_default_row')}))<={tol},1,0)")

        # 3. Recovery conservation: Σ recoveries == recovery_pct × Σ defaults.
        c3 = (f"=IF(ABS({lt_sum('pool_recovery_row')}"
              f"-recovery_pct*{lt_sum('pool_default_row')})<={tol},1,0)")

        # 3b. Recovery TIMING: each non-final period's recovery == recovery_pct ×
        #     default[t−lag] (catches a mis-timed recovery profile that #3's total
        #     would mask). The final period legitimately sweeps the tail.
        c3b = []
        for i in range(1, periods):
            col = layout.year_col(i)
            if i - lag >= 1:
                src = f"recovery_pct*{lt(layout.year_col(i-lag),'pool_default_row')}"
            else:
                src = "0"
            c3b.append(f"ABS({lt(col,'pool_recovery_row')}-({src}))<={tol}")

        # 4. Principal strictly sequential: a junior debt note amortizes only once
        #    every more-senior debt note is retired (EOP≈0). NON-VACUOUS: a
        #    mis-ordered principal waterfall fails it. (residual is not a plug here.)
        c4 = []
        for col in proj:
            for idx, j in enumerate(debt):
                if idx == 0:
                    continue
                seniors = "+".join(wf(col, f"eop_{debt[k]}_row") for k in range(idx))
                c4.append(f"OR({wf(col, f'prin_paid_{j}_row')}<={tol},({seniors})<={tol})")

        # 4t. Turbo is strictly sequential too: a junior debt note's turbo paydown
        #     only fires once every more-senior debt note is retired. NON-VACUOUS:
        #     a junior-first turbo (seniority inversion) breaks it — closes the gap
        #     that scheduled-principal #4 covers but the turbo legs did not.
        c4t = []
        for col in proj:
            for idx, j in enumerate(debt):
                if idx == 0:
                    continue
                seniors = "+".join(wf(col, f"eop_{debt[k]}_row") for k in range(idx))
                c4t.append(f"OR({wf(col, f'turbo_{j}_row')}<={tol},({seniors})<={tol})")

        # 5. Interest paid is bounded by what is due and never negative, for EVERY
        #    note. NON-VACUOUS: a negative coupon or an over-payment breaks it.
        c5 = []
        for col in proj:
            for j in debt:
                c5.append(f"{wf(col, f'int_paid_{j}_row')}>=-{tol}")
                c5.append(f"{wf(col, f'int_paid_{j}_row')}<={wf(col, f'int_due_{j}_row')}+{tol}")

        # 6. Senior interest paid == due every period (senior fully serviced, base case).
        c6 = [f"ABS({wf(col, f'int_paid_{senior}_row')}-{wf(col, f'int_due_{senior}_row')})<={tol}"
              for col in proj]

        # 7. Residual interest to equity never negative (no excess-spread leak).
        c7 = [f"{wf(col,'residual_int_to_equity_row')}>=-{tol}" for col in proj]

        # 8. Subordination: residual principal only once ALL debt is retired.
        c8 = []
        for col in proj:
            debt_eop = "+".join(wf(col, f"eop_{j}_row") for j in debt)
            c8.append(f"OR({wf(col,'prin_to_residual_row')}<={tol},({debt_eop})<={tol})")

        # 9. Every note outstanding ≥ 0 each period.
        c9 = [f"{wf(col, f'eop_{j}_row')}>=-{tol}" for col in cols for j in range(n_notes)]

        # 10. Note balances monotone non-increasing (no note grows).
        c10 = []
        for i in range(1, n):
            col = layout.year_col(i); prior = layout.year_col(i - 1)
            for j in range(n_notes):
                c10.append(f"{wf(col, f'eop_{j}_row')}<={wf(prior, f'eop_{j}_row')}+{tol}")

        # 11. Senior note fully redeemed by maturity (deal performs).
        c11 = f"=IF({wf(last, f'eop_{senior}_row')}<={tol},1,0)"

        # 12. No excess spread to equity during an UNRESOLVED OC/IC breach while a
        #     debt note remains outstanding. NON-VACUOUS: catches the turbo leaking
        #     to equity instead of curing the senior-most outstanding note.
        c12 = []
        for col in proj:
            debt_eop = "+".join(wf(col, f"eop_{j}_row") for j in debt)
            c12.append(
                f"OR({wf(col,'residual_int_to_equity_row')}<={tol},"
                f"AND({wf(col,'oc_pass_row')}=1,{wf(col,'ic_pass_row')}=1),"
                f"({debt_eop})<={tol})")

        # 13. Reserve returns to equity only once ALL debt is retired (no priority
        #     inversion). NON-VACUOUS: catches the maturity reserve release leaking
        #     to first-loss equity while a senior/mezz note is still impaired.
        c13 = []
        for col in proj:
            debt_eop = "+".join(wf(col, f"eop_{j}_row") for j in debt)
            c13.append(f"OR({wf(col,'reserve_to_equity_row')}<={tol},({debt_eop})<={tol})")

        checks = [
            ("Pool roll-forward telescopes (BOP[t] = EOP[t−1])",
             "Roll-forward pool coerente", _all(c1)),
            ("Scheduled+prepay principal closes the pool (= initial − Σdefault)",
             "Capitale programmato+prepay chiude il pool", c2),
            ("Recovery conservation (Σrec = recovery% × Σdef)",
             "Conservazione recuperi", c3),
            ("Recovery timing correct each period (rec[t] = recovery% × def[t−lag])",
             "Tempistica recuperi corretta", _all(c3b) if c3b else "=1"),
            ("Principal strictly sequential (junior pays only after seniors retired)",
             "Capitale strettamente sequenziale", _all(c4) if c4 else "=1"),
            ("Turbo strictly sequential (junior turbo only after seniors retired)",
             "Turbo strettamente sequenziale", _all(c4t) if c4t else "=1"),
            ("Interest paid within [0, due] for every note (no negative coupon)",
             "Interessi pagati entro [0, dovuto]", _all(c5)),
            ("Senior interest paid = due every period (not shorted)",
             "Interessi senior pagati = dovuti", _all(c6)),
            ("Residual interest to equity never negative",
             "Interessi residui all'equity ≥ 0", _all(c7)),
            ("Subordination: residual principal only after debt retired",
             "Subordinazione: capitale residuale dopo le note debito", _all(c8)),
            ("Every note outstanding ≥ 0 each period",
             "Saldo note ≥ 0 ogni periodo", _all(c9)),
            ("Note balances monotone non-increasing",
             "Saldi note non crescenti", _all(c10)),
            ("Senior note fully redeemed by maturity",
             "Nota senior interamente rimborsata a scadenza", c11),
            ("No excess spread to equity during an unresolved OC/IC breach",
             "Nessuno spread all'equity durante un breach OC/IC", _all(c12)),
            ("Reserve returns to equity only after all debt is retired",
             "Riserva all'equity solo dopo il rimborso del debito", _all(c13)),
        ]
        qc_ws = wb.create_sheet("QC")
        generic_qc.build(qc_ws, checks)

        compliance_ws = wb.create_sheet("ComplianceCheck")
        compliance_sheet.build(compliance_ws, spec)
        return {}

    return build_base_workbook(spec, out_path, core_sheets, graph_db_path)[:2]
