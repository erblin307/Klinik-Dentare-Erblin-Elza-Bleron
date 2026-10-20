import type { NextConfig } from "next";

// Server-side only: the browser talks to this site, which forwards API calls
// to Django. Same origin, so no CORS and no backend address in the client.
const djangoApiUrl = (process.env.DJANGO_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    // Django's URLs end with "/"; the site's do not.
    return [
      { source: "/api/chat/:path*", destination: `${djangoApiUrl}/api/chat/:path*/` },
      { source: "/api/public/:path*", destination: `${djangoApiUrl}/api/public/:path*/` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
