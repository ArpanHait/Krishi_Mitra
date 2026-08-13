import { NextResponse } from 'next/server';

export const revalidate = 0;

export async function POST() {
  const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;

  const targetUrl = backendUrl
    ? `${backendUrl.replace(/\/$/, '')}/api/escalations/sync-email`
    : 'http://localhost:8080/api/escalations/sync-email';

  try {
    const res = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Bypass-Tunnel-Reminder': 'true',
        'User-Agent': 'Mozilla/5.0',
      },
    });

    if (!res.ok) {
      console.error(`Sync email response failed with status ${res.status}`);
      return NextResponse.json(
        { success: false, error: `Backend responded with status ${res.status}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error posting sync-email to backend REST API:', error);
    return NextResponse.json({ success: false, error: 'Failed to sync emails' }, { status: 500 });
  }
}
