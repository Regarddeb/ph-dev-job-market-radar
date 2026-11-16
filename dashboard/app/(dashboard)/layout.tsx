import { Nav } from "@/components/nav";
import { SiteFooter } from "@/components/site-footer";

export default function DashboardLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <a
        href="#main"
        className="bg-background sr-only z-50 rounded-md border px-3 py-2 text-sm focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <Nav />
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        {children}
      </main>
      <SiteFooter />
    </>
  );
}
