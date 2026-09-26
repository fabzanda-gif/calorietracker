import "./activities-fixes.css";
import ActivitiesUiGuard from "./ActivitiesUiGuard";

export default function ActivitiesLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <ActivitiesUiGuard />
      {children}
    </>
  );
}
