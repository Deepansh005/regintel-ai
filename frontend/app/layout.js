import "../styles/globals.css";

export const metadata = {
  title: "RegIntel AI",
  description: "AI-powered regulatory analysis",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}