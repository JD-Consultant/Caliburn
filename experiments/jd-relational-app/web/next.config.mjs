import { fileURLToPath } from 'node:url';

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  poweredByHeader: false,
  // pnpm hoists the shared dependency graph to the repository workspace root.
  turbopack: { root: fileURLToPath(new URL('../../..', import.meta.url)) },
};
export default config;
