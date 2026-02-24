import type { ReactNode } from "react";

const iconClass = "w-[72px] h-[72px] mb-4";
const iconClassActive = `${iconClass} text-primary`;
const iconClassInactive = `${iconClass} text-gray-400`;

export interface Station {
  id: string;
  title: string;
  description: string;
  active: boolean;
  path: string;
  icon: ReactNode;
}

function IconGrill({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.08-2.143-.22-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
    </svg>
  );
}

function IconPizza({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2v20M2 12h20" />
      <circle cx="8" cy="10" r="1.5" fill="currentColor" />
      <circle cx="16" cy="14" r="1.5" fill="currentColor" />
    </svg>
  );
}

function IconEntree({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <ellipse cx="12" cy="14" rx="8" ry="3" />
      <path d="M5 14V8a3 3 0 0 1 6 0v6M13 14V8a3 3 0 0 1 6 0v6" />
    </svg>
  );
}

function IconTrueBalan({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M4 7h16M12 7v6M12 13l-4 5M12 13l4 5" />
      <circle cx="8" cy="18" r="2" />
      <circle cx="16" cy="18" r="2" />
    </svg>
  );
}

function IconHalalStree({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M12 2l1.5 4.5L18 8l-3.5 2.5L16 15l-4-2.5L8 15l1.5-4.5L6 8l4.5-1.5L12 2z" />
    </svg>
  );
}

function IconVegan({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
    </svg>
  );
}

function IconDeli({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
      <path d="M7 2v20" />
      <path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
    </svg>
  );
}

function IconSaladBar({ active }: { active: boolean }) {
  return (
    <svg
      className={active ? iconClassActive : iconClassInactive}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M12 22c-4.97 0-9-2.58-9-6s4.03-6 9-6 9 2.58 9 6-4.03 6-9-6Z" />
      <path d="M12 10c-2.76 0-5-1.12-5-2.5S9.24 5 12 5s5 1.12 5 2.5-2.24 2.5-5 2.5Z" />
    </svg>
  );
}

export const stations: readonly Station[] = [
  {
    id: "grill",
    title: "Grill",
    description: "Breakfast, lunch & dinner menu – view and analyze.",
    active: true,
    path: "/meal-period",
    icon: <IconGrill active={true} />,
  },
  {
    id: "pizza",
    title: "Pizza",
    description: "Coming soon.",
    active: false,
    path: "",
    icon: <IconPizza active={false} />,
  },
  {
    id: "entree",
    title: "Entree",
    description: "Coming soon.",
    active: false,
    path: "",
    icon: <IconEntree active={false} />,
  },
  {
    id: "true-balan",
    title: "True Balan",
    description: "Coming soon.",
    active: false,
    path: "",
    icon: <IconTrueBalan active={false} />,
  },
  {
    id: "halal-stree",
    title: "Halal Stree",
    description: "Coming soon.",
    active: false,
    path: "",
    icon: <IconHalalStree active={false} />,
  },
  {
    id: "vegan",
    title: "Vegan",
    description: "Coming soon.",
    active: false,
    path: "",
    icon: <IconVegan active={false} />,
  },
  {
    id: "deli",
    title: "Deli",
    description: "Coming soon.",
    active: false,
    path: "",
    icon: <IconDeli active={false} />,
  },
  {
    id: "saladbar",
    title: "Salad Bar",
    description: "Coming soon.",
    active: false,
    path: "",
    icon: <IconSaladBar active={false} />,
  },
];
