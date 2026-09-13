import Workspace from '../components/Workspace';
export const dynamic = 'force-dynamic';
export default function Page() {
  // One explicit public loopback endpoint, supplied by the local launcher.
  // It contains no database credentials and never supplies domain defaults.
  return <Workspace apiOrigin={process.env.JD_API_ORIGIN ?? null} />;
}
