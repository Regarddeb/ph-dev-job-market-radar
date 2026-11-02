import { Nav } from "@/components/nav";

export default function DashboardLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <Nav />
      <main className="mx-auto w-full max-w-6xl flex-1 p-6">{children}</main>
    </>
  );
}
