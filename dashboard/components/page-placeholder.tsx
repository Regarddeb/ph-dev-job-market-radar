export function PagePlaceholder({ title, plan }: { title: string; plan: string }) {
  return (
    <section className="space-y-2">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-muted-foreground">{plan}</p>
    </section>
  );
}
