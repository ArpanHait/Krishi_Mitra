import { NextResponse } from 'next/server';
import { DatabaseSync } from 'node:sqlite';
import path from 'path';

export const revalidate = 0;

function getDb() {
  const dbPath = path.resolve(process.cwd(), '..', 'backend', 'krishi_memory.db');
  const db = new DatabaseSync(dbPath);
  db.exec(`
    CREATE TABLE IF NOT EXISTS escalations (
        ticket_id TEXT PRIMARY KEY,
        farmer_name TEXT,
        topic TEXT,
        summary TEXT,
        urgency TEXT CHECK(urgency IN ('Low', 'Medium', 'High', 'Emergency')),
        status TEXT DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED')),
        language TEXT,
        preferred_followup TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
  `);
  return db;
}

export async function GET() {
  try {
    const db = getDb();
    const query = db.prepare('SELECT * FROM escalations ORDER BY created_at DESC');
    const rows = query.all();
    db.close();
    return NextResponse.json(rows);
  } catch (error) {
    console.error('Error fetching escalations:', error);
    return NextResponse.json({ error: 'Failed to fetch escalations' }, { status: 500 });
  }
}
