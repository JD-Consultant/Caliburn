import { JdWorkspace } from "../../../jd/JdWorkspace";
export default async function Page({
  params,
}: {
  params: Promise<{ document_id: string }>;
}) {
  const { document_id } = await params;
  return <JdWorkspace key={document_id} document={document_id} />;
}
