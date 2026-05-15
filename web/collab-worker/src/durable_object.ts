/**
 * CollabDoc Durable Object — owns one Y.Doc per workbook.
 *
 * Each tenant-scoped doc id maps to one DO instance (long-lived in CF's
 * edge memory while WS clients are connected; persisted to DO storage
 * between connection windows).
 *
 * State model:
 *   ymap "comments"   — mirror of Python CommentStore events (append-only)
 *   ymap "review"     — current ReviewState snapshot
 *   ymap "presence"   — ephemeral cursor positions per active user
 *
 * On WebSocket connect: sync handshake (y-protocols sync step 1/2) +
 * awareness exchange. Every Y.Doc update is persisted to DO storage
 * under "y-doc-state" so reconnects pick up where we left off.
 */

import * as Y from "yjs";
import * as syncProtocol from "y-protocols/sync";
import * as awarenessProtocol from "y-protocols/awareness";
import { encoding, decoding } from "lib0";

const MESSAGE_SYNC = 0;
const MESSAGE_AWARENESS = 1;

interface ConnectedClient {
  ws: WebSocket;
  userId: string;
  tenantId: string;
  awarenessState: number | null;
}

export class CollabDoc {
  private state: DurableObjectState;
  private env: { COLLAB_DOC: DurableObjectNamespace; ENV: string };
  private doc: Y.Doc;
  private awareness: awarenessProtocol.Awareness;
  private clients: Set<ConnectedClient>;
  private dirty: boolean;
  private persistTimer: ReturnType<typeof setTimeout> | null;

  constructor(state: DurableObjectState, env: { COLLAB_DOC: DurableObjectNamespace; ENV: string }) {
    this.state = state;
    this.env = env;
    this.doc = new Y.Doc();
    this.awareness = new awarenessProtocol.Awareness(this.doc);
    this.clients = new Set();
    this.dirty = false;
    this.persistTimer = null;

    // Restore persisted state on first access
    this.state.blockConcurrencyWhile(async () => {
      const stored = await this.state.storage.get<Uint8Array>("y-doc-state");
      if (stored) {
        Y.applyUpdate(this.doc, stored);
      }
    });

    this.doc.on("update", (update: Uint8Array, origin: unknown) => {
      // Broadcast to all OTHER clients (origin already has it)
      this.broadcastUpdate(update, origin);
      this.markDirty();
    });

    this.awareness.on("update", (
      { added, updated, removed }: { added: number[]; updated: number[]; removed: number[] },
      origin: unknown,
    ) => {
      this.broadcastAwareness([...added, ...updated, ...removed], origin);
    });
  }

  async fetch(req: Request): Promise<Response> {
    const action = req.headers.get("X-MF-Action");
    const userId = req.headers.get("X-MF-User-Id") ?? "anon";
    const tenantId = req.headers.get("X-MF-Tenant-Id") ?? "default";

    if (action === "ws") {
      // WebSocket upgrade
      const upgradeHeader = req.headers.get("Upgrade");
      if (upgradeHeader !== "websocket") {
        return new Response("expected WebSocket upgrade", { status: 426 });
      }
      const pair = new WebSocketPair();
      const [client, server] = [pair[0], pair[1]];
      this.acceptClient(server, userId, tenantId);
      return new Response(null, { status: 101, webSocket: client });
    }

    if (action === "snapshot") {
      // Return the encoded Y.Doc state vector + state update for cold-start sync
      const stateVector = Y.encodeStateVector(this.doc);
      const update = Y.encodeStateAsUpdate(this.doc);
      return new Response(update, {
        headers: {
          "Content-Type": "application/octet-stream",
          "X-MF-State-Vector": btoa(String.fromCharCode(...stateVector)),
        },
      });
    }

    if (action === "comments" && req.method === "POST") {
      // REST mirror endpoint — Python CommentStore can POST events here
      // and they merge into the Y.Doc's "comments" map.
      const body = (await req.json()) as Record<string, unknown>;
      const comments = this.doc.getMap("comments");
      const entryKey = (body["id"] as string) ?? crypto.randomUUID();
      this.doc.transact(() => {
        comments.set(entryKey, body);
      });
      return new Response(JSON.stringify({ ok: true, id: entryKey }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    if (action === "comments" && req.method === "GET") {
      const comments = this.doc.getMap("comments");
      const all: Record<string, unknown>[] = [];
      comments.forEach((value, key) => {
        all.push({ id: key, ...((value ?? {}) as Record<string, unknown>) });
      });
      return new Response(JSON.stringify({ comments: all }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response("unsupported action", { status: 400 });
  }

  private acceptClient(ws: WebSocket, userId: string, tenantId: string): void {
    ws.accept();
    const client: ConnectedClient = { ws, userId, tenantId, awarenessState: null };
    this.clients.add(client);

    // Initial sync — server sends its sync step 1 + state update
    {
      const enc = encoding.createEncoder();
      encoding.writeVarUint(enc, MESSAGE_SYNC);
      syncProtocol.writeSyncStep1(enc, this.doc);
      ws.send(encoding.toUint8Array(enc));
    }
    // Initial awareness state
    if (this.awareness.getStates().size > 0) {
      const enc = encoding.createEncoder();
      encoding.writeVarUint(enc, MESSAGE_AWARENESS);
      encoding.writeVarUint8Array(
        enc,
        awarenessProtocol.encodeAwarenessUpdate(
          this.awareness,
          Array.from(this.awareness.getStates().keys()),
        ),
      );
      ws.send(encoding.toUint8Array(enc));
    }

    ws.addEventListener("message", (event: MessageEvent) => {
      const data = new Uint8Array(event.data as ArrayBuffer);
      const dec = decoding.createDecoder(data);
      const messageType = decoding.readVarUint(dec);
      const enc = encoding.createEncoder();
      switch (messageType) {
        case MESSAGE_SYNC: {
          encoding.writeVarUint(enc, MESSAGE_SYNC);
          syncProtocol.readSyncMessage(dec, enc, this.doc, client);
          if (encoding.length(enc) > 1) ws.send(encoding.toUint8Array(enc));
          break;
        }
        case MESSAGE_AWARENESS: {
          awarenessProtocol.applyAwarenessUpdate(
            this.awareness,
            decoding.readVarUint8Array(dec),
            client,
          );
          break;
        }
      }
    });

    ws.addEventListener("close", () => {
      this.clients.delete(client);
      awarenessProtocol.removeAwarenessStates(
        this.awareness,
        [client.awarenessState ?? this.doc.clientID],
        client,
      );
    });

    ws.addEventListener("error", () => {
      this.clients.delete(client);
    });
  }

  private broadcastUpdate(update: Uint8Array, origin: unknown): void {
    const enc = encoding.createEncoder();
    encoding.writeVarUint(enc, MESSAGE_SYNC);
    syncProtocol.writeUpdate(enc, update);
    const buf = encoding.toUint8Array(enc);
    for (const c of this.clients) {
      if (c === origin) continue;
      try {
        c.ws.send(buf);
      } catch {
        this.clients.delete(c);
      }
    }
  }

  private broadcastAwareness(changedClients: number[], origin: unknown): void {
    const enc = encoding.createEncoder();
    encoding.writeVarUint(enc, MESSAGE_AWARENESS);
    encoding.writeVarUint8Array(
      enc,
      awarenessProtocol.encodeAwarenessUpdate(this.awareness, changedClients),
    );
    const buf = encoding.toUint8Array(enc);
    for (const c of this.clients) {
      if (c === origin) continue;
      try {
        c.ws.send(buf);
      } catch {
        this.clients.delete(c);
      }
    }
  }

  private markDirty(): void {
    this.dirty = true;
    if (this.persistTimer) return;
    // Debounce persistence by 1s to coalesce bursts
    this.persistTimer = setTimeout(() => {
      this.persistTimer = null;
      if (!this.dirty) return;
      this.dirty = false;
      const update = Y.encodeStateAsUpdate(this.doc);
      this.state.storage.put("y-doc-state", update);
    }, 1000);
  }
}
