import CompteLayoutClient from './CompteLayoutClient';

export const metadata = { robots: { index: false, follow: true } };

export default function CompteLayout({ children }) {
  return <CompteLayoutClient>{children}</CompteLayoutClient>;
}
