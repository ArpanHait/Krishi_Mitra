export const dynamic = 'force-dynamic';

export async function GET() {
  const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL;
  const targetUrl = backendUrl
    ? `${backendUrl.replace(/\/$/, '')}/api/events`
    : 'http://localhost:8080/api/events';

  try {
    const response = await fetch(targetUrl, {
      headers: {
        Accept: 'text/event-stream',
        'Bypass-Tunnel-Reminder': 'true',
        'localtunnel-bypass-warning': 'true',
        'ngrok-skip-browser-warning': 'true',
      },
    });

    if (!response.ok || !response.body) {
      return new Response('SSE connection failed', { status: response.status || 500 });
    }

    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
      },
    });
  } catch (error) {
    console.error('Error connecting to SSE stream:', error);
    return new Response('SSE connection error', { status: 500 });
  }
}
