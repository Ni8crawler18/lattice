import { Inter, JetBrains_Mono, Silkscreen } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

const pixel = Silkscreen({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-pixel",
  display: "swap",
});

export const metadata = {
  title: "Lattice — Indian Address Intelligence",
  description:
    "Parse, resolve and score Indian addresses. Built on the Sarvam stack.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} ${pixel.variable}`}>
      <body>{children}</body>
    </html>
  );
}
