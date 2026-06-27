import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listProfiles, getProfile, createProfile, deleteProfile } from "@/lib/api";
import { useUserStore } from "@/store/user";

export function useProfiles() {
  const userId = useUserStore((s) => s.userId);
  return useQuery({
    queryKey: ["profiles", userId],
    queryFn: () => listProfiles(userId!),
    enabled: !!userId,
  });
}

export function useProfile(profileId: string) {
  return useQuery({
    queryKey: ["profile", profileId],
    queryFn: () => getProfile(profileId),
    refetchInterval: false,
  });
}

export function useCreateProfile() {
  const qc = useQueryClient();
  const ensureUser = useUserStore((s) => s.ensureUser);
  return useMutation({
    mutationFn: async (data: { job_title: string; department?: string; job_summary?: string }) => {
      const userId = await ensureUser();
      return createProfile(userId, data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profiles"] }),
  });
}

export function useDeleteProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profiles"] }),
  });
}
