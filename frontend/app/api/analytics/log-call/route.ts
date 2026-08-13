import { NextResponse } from 'next/server';

export const revalidate = 0;

export async function POST(request: Request) {
  const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;

  const targetUrl = backendUrl
    ? `${backendUrl.replace(/\/$/, '')}/api/analytics/log-call`
    : 'http://localhost:8080/api/analytics/log-call';

  try {
    const body = await request.json();
    const res = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Bypass-Tunnel-Reminder': 'true',
        'User-Agent': 'Mozilla/5.0',
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      console.error(`Log call response failed with status ${res.status}`);
      return NextResponse.json(
        { success: false, error: `Backend responded with status ${res.status}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error posting log-call to backend REST API:', error);
    return NextResponse.json({ success: false, error: 'Failed to log call' }, { status: 500 });
  }
}
