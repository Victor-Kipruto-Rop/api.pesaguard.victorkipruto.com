import { AccordionGroup, AccordionItem } from "@/components/ui/Accordion";
import type { FaqItem } from "@/types/content";

/**
 * Frequently asked questions.
 *
 * Built on `details`/`summary`, so answers are in the DOM for search engines and
 * usable without JavaScript. The first answer is closed by default: these are
 * reference answers, not a wall the reader has to scroll past.
 */
export function Faq({ items }: { items: FaqItem[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <AccordionGroup>
      {items.map((item) => (
        <AccordionItem key={item.question} title={item.question}>
          <p>{item.answer}</p>
        </AccordionItem>
      ))}
    </AccordionGroup>
  );
}