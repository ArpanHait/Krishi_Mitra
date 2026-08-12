import { NextResponse } from 'next/server';
import { DatabaseSync } from 'node:sqlite';
import path from 'path';

export const revalidate = 0;

function getDb() {
  const dbPath = path.resolve(process.cwd(), '..', 'backend', 'krishi_memory.db');
  return new DatabaseSync(dbPath);
}

export async function POST(req: Request) {
  try {
    const { ticket_id } = await req.json();
    if (!ticket_id) {
      return NextResponse.json({ error: 'Missing ticket_id' }, { status: 400 });
    }

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
