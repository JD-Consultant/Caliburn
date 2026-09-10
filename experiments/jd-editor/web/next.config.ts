import type { NextConfig } from "next";
const config: NextConfig = {
  transpilePackages: [
    "@caliburn/jd-editor-native",
    "@caliburn/jd-editor-contract",
  ],
};
export default config;
