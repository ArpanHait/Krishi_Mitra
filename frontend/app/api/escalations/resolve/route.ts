import { NextResponse } from 'next/server';
import { DatabaseSync } from 'node:sqlite';
import path from 'path';

export const revalidate = 0;

function getDb() {
  const dbPath = path.resolve(process.cwd(), '..', 'backend', 'krishi_memory.db');
  return new DatabaseSync(dbPath);
}

export async function POST(req: Request) {
  const body = await req.json();
  const { ticket_id } = body;
  if (!ticket_id) {
    return NextResponse.json({ error: 'Missing ticket_id' }, { status: 400 });
  }

  const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;

  if (backendUrl) {
    try {
      const res = await fetch(`${backendUrl.replace(/\/$/, '')}/api/escalations/resolve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Bypass-Tunnel-Reminder': 'true',
          'User-Agent': 'Mozilla/5.0',
        },
        body: JSON.stringify({ ticket_id }),
      });
      const data = await res.json();
      return NextResponse.json(data);
    } catch (error) {
      console.error('Error posting resolve to backend REST API:', error);
      return NextResponse.json({ error: 'Failed to resolve on backend' }, { status: 500 });
    }
  }

  try {
    const db = getDb();
    const updateQuery = db.prepare(
      "UPDATE escalations SET status = 'RESOLVED', has_unread_reply = 0, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?"
    );
    updateQuery.run(ticket_id);

    // Auto-prune resolved tickets beyond 3 entries
    const pruneQuery = db.prepare(`
      DELETE FROM escalations 
      WHERE status = 'RESOLVED' 
      AND ticket_id NOT IN (
          SELECT ticket_id FROM escalations 
          WHERE status = 'RESOLVED' 
          ORDER BY updated_at DESC 
          LIMIT 3
      );
    `);
    pruneQuery.run();
    db.close();

    return NextResponse.json({ success: true, ticket_id });
  } catch (error) {
    console.error('Error resolving escalation ticket:', error);
    return NextResponse.json({ error: 'Failed to resolve' }, { status: 500 });
  }
}
