import { NextResponse } from 'next/server';

export const revalidate = 0;

export async function GET() {
  const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;

  const targetUrl = backendUrl
    ? `${backendUrl.replace(/\/$/, '')}/api/analytics`
    : 'http://localhost:8080/api/analytics';

  try {
    const res = await fetch(targetUrl, {
      headers: {
        'Bypass-Tunnel-Reminder': 'true',
        'localtunnel-bypass-warning': 'true',
        'ngrok-skip-browser-warning': 'true',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      },
    });

    if (!res.ok) {
      console.error(`Analytics response failed with status ${res.status}`);
      return NextResponse.json(
        { error: `Backend responded with status ${res.status}` },
        { status: res.status }
      );
    }

    const text = await res.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data);
    } catch {
      console.error('Backend returned HTML landing page instead of JSON:', text.slice(0, 150));
      return NextResponse.json(
        {
          total_calls: 0,
          successful_calls: 0,
          declined_calls: 0,
          system_failed_calls: 0,
          failed_calls: 0,
          success_rate: 0.0,
          recent_logs: [],
          error: 'Tunnel password page returned instead of backend JSON',
        },
        { status: 200 }
      );
    }
  } catch (error) {
    console.error('Error fetching analytics from backend REST API:', error);
    return NextResponse.json(
      {
        total_calls: 0,
        successful_calls: 0,
        failed_calls: 0,
        success_rate: 0.0,
        recent_logs: [],
        error: 'Failed to connect to backend analytics service',
      },
      { status: 500 }
    );
  }
}
