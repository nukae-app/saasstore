import CarretClient from './CarretClient';

export const metadata = { robots: { index: false, follow: true } };

export default function CarretPage() {
  return <CarretClient />;
}
