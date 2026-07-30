import { TaskEditor } from "@/components/workspace/TaskEditor";

export default async function DocumentWorkspacePage({
  params,
}: {
  params: Promise<{ document_id: string }>;
}) {
  const { document_id } = await params;
  return <TaskEditor documentId={document_id} />;
}
