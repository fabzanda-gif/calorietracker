import { GuidedWorkoutPage } from "@/components/activity/GuidedWorkoutPage";

export default async function WorkoutPage({ params }: { params: Promise<{ session: string[] }> }) {
  const { session } = await params;
  return <GuidedWorkoutPage session={session} />;
}
