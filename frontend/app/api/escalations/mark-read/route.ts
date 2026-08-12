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
      const res = await fetch(`${backendUrl.replace(/\/$/, '')}/api/escalations/mark-read`, {
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
      console.error('Error posting mark-read to backend REST API:', error);
      return NextResponse.json({ error: 'Failed to update backend' }, { status: 500 });
    }
  }

  try {
    const db = getDb();
    const query = db.prepare('UPDATE escalations SET has_unread_reply = 0 WHERE ticket_id = ?');
    query.run(ticket_id);
    db.close();

    return NextResponse.json({ success: true, ticket_id });
  } catch (error) {
    console.error('Error marking escalation reply as read:', error);
    return NextResponse.json({ error: 'Failed to update' }, { status: 500 });
  }
}
