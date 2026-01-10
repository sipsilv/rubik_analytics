/** @type {import('next').NextConfig} */
const path = require('path')

const nextConfig = {
  reactStrictMode: true,
<<<<<<< HEAD
  output: 'standalone',
  eslint: {
    // Disable ESLint during production builds
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Disable TypeScript errors during production builds
    ignoreBuildErrors: true,
  },
=======

  experimental: {
    outputFileTracingRoot: path.join(__dirname, '../../'),
  }
>>>>>>> 8e1afed (adjusted it for production code)
}

module.exports = nextConfig

