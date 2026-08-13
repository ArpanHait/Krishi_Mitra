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
        status TEXT DEFAULT 'OPEN',
        language TEXT,
        preferred_followup TEXT,
        officer_response TEXT DEFAULT NULL,
        has_unread_reply INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
  `);
  return db;
}

export async function GET() {
  const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;

  if (backendUrl) {
    try {
      const res = await fetch(`${backendUrl.replace(/\/$/, '')}/api/escalations/pending-count`, {
        cache: 'no-store',
        headers: {
          'Bypass-Tunnel-Reminder': 'true',
          'localtunnel-bypass-warning': 'true',
          'User-Agent': 'Mozilla/5.0',
        },
      });
      const data = await res.json();
      return NextResponse.json(data);
    } catch (error) {
      console.error('Error fetching pending count from backend REST API:', error);
      return NextResponse.json({ count: 0, has_unread_replies: false, unread_count: 0 });
    }
  }

  try {
    const db = getDb();
    const openQuery = db.prepare("SELECT COUNT(*) as count FROM escalations WHERE status = 'OPEN'");
    const openResult = openQuery.get() as { count: number };

    let unreadCount = 0;
    try {
      const unreadQuery = db.prepare(
        'SELECT COUNT(*) as count FROM escalations WHERE has_unread_reply = 1'
      );
      const unreadResult = unreadQuery.get() as { count: number };
      unreadCount = unreadResult?.count || 0;
    } catch {
      unreadCount = 0;
    }

    db.close();
    return NextResponse.json({
      count: openResult?.count || 0,
      has_unread_replies: unreadCount > 0,
      unread_count: unreadCount,
    });
  } catch (error) {
    console.error('Error fetching pending count:', error);
    return NextResponse.json({ count: 0, has_unread_replies: false, unread_count: 0 });
  }
}
