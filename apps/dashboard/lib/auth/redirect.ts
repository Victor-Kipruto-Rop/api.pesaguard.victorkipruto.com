export function safePostLoginDestination(value: string | null): string {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/overview";
}
