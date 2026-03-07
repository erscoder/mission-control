/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['lucide-react'],
  rewrites: async () => [
    {
      source: '/api/ws',
      destination: 'http://localhost:18789/ws',
    },
    {
      source: '/api/gateway/:path*',
      destination: 'http://localhost:18789/:path*',
    },
  ],
}

module.exports = nextConfig
