import type { Metadata } from "next";
import "./globals.css";
import Shell from "@/components/Shell";

export const metadata: Metadata = {
  title: "AI Order Supervisor",
  description:
    "Operator console for the long-running AI order supervisor (Temporal + FastAPI).",
};

// Runs before first paint: dark by default, remembers the user's choice,
// otherwise follows the system preference. Without this the .dark variables
// never activate.
const themeBoot = `(function(){try{var t=localStorage.getItem("theme");if(t!=="light"){document.documentElement.classList.add("dark")}}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
      </head>
      <body className="min-h-screen bg-bg text-txt font-sans antialiased">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
