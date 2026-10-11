export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-svh flex-col bg-background px-4 py-8 text-foreground sm:px-6 sm:py-12">
      <div className="mx-auto my-auto w-full max-w-md">{children}</div>
    </main>
  );
}
