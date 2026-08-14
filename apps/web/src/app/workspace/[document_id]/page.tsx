import { ConsultantWorkspace } from "@/features/consultant";

export default async function DocumentWorkspacePage({
  params,
}: {
  params: Promise<{ document_id: string }>;
}) {
  const { document_id } = await params;
  return <ConsultantWorkspace documentId={document_id} />;
}
