import type { NextConfig } from "next";
import { validatePublicConfig } from "./lib/public-config";

if (process.env.NODE_ENV === "production") validatePublicConfig(process.env);

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
