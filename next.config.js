/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_GATEWAY_TOKEN: '0a89ee11390e477248cf3db7774279d89d4df35fcae28ccd714921d80c2af1ae',
    NEXT_PUBLIC_GATEWAY_HOST: '127.0.0.1',
    NEXT_PUBLIC_GATEWAY_PORT: '18789',
  },

  // Serve static MkDocs site
  async rewrites() {
    return [
      {
        source: '/docs-site/:path*',
        destination: '/docs-site/:path*',
      },
    ];
  },
};

export default nextConfig;
