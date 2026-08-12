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
  try {
    const body = await req.json();
    const { ticket_id, status } = body;

    if (!ticket_id || !status) {
      return NextResponse.json({ error: 'Missing ticket_id or status' }, { status: 400 });
    }

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
