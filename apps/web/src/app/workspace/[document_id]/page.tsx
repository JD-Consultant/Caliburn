import { ConsultationWorkspace } from "@/components/workspace/ConsultationWorkspace";

export default async function DocumentWorkspacePage({
  params,
}: {
  params: Promise<{ document_id: string }>;
}) {
  const { document_id } = await params;
  return <ConsultationWorkspace documentId={document_id} />;
}
