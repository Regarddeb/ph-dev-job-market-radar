import { PagePlaceholder } from "@/components/page-placeholder";

export default function OpsPage() {
  return (
    <PagePlaceholder
      title="Ops"
      plan="Crawl runs per source, last successful run (flag over 48 h), and DB size (warn over 800 MB)."
    />
  );
}
