/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Proxy API calls to the FastAPI backend in development so the browser sees a
    // single origin and CORS stays out of the way.
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_ORIGIN ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
