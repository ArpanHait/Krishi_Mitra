import { NextResponse } from 'next/server';
import { DatabaseSync } from 'node:sqlite';
import path from 'path';

export const revalidate = 0;

function getDb() {
  const dbPath = path.resolve(process.cwd(), '..', 'backend', 'krishi_memory.db');
  const db = new DatabaseSync(dbPath);
  return db;
}

export async function POST(req: Request) {
  const body = await req.json();
  const { ticket_id, status } = body;

  if (!ticket_id || !status) {
    return NextResponse.json({ error: 'Missing ticket_id or status' }, { status: 400 });
  }

  const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;

  if (backendUrl) {
    try {
      const res = await fetch(`${backendUrl.replace(/\/$/, '')}/api/escalations/update-status`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Bypass-Tunnel-Reminder': 'true',
          'User-Agent': 'Mozilla/5.0',
        },
        body: JSON.stringify({ ticket_id, status }),
      });
      const data = await res.json();
      return NextResponse.json(data);
    } catch (error) {
      console.error('Error posting update-status to backend REST API:', error);
      return NextResponse.json({ error: 'Failed to update backend' }, { status: 500 });
    }
  }

  try {
    const db = getDb();
    const now = new Date().toISOString();
    const statement = db.prepare(
      'UPDATE escalations SET status = ?, updated_at = ? WHERE ticket_id = ?'
    );
    statement.run(status, now, ticket_id);
    db.close();

    return NextResponse.json({ success: true, ticket_id, status });
  } catch (error) {
    console.error('Error updating escalation status:', error);
    return NextResponse.json({ error: 'Failed to update status' }, { status: 500 });
  }
}
