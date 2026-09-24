import { ButtonLink, Container } from "@/components/ui";

export default function NotFound() {
  return (
    <Container className="py-32 text-center">
      <p className="text-sm text-muted">404</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">This page isn&apos;t in the archive</h1>
      <div className="mt-8 flex justify-center gap-3">
        <ButtonLink href="/" primary>
          Back to the overview
        </ButtonLink>
        <ButtonLink href="/archive">Browse the archive</ButtonLink>
      </div>
    </Container>
  );
}
