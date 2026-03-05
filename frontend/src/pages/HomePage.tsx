import { Link } from "react-router-dom";
import { AramarkLogo } from "../components/AramarkLogo";
import { stationSlugFromTitle, stations } from "../data/stations";

const cardBase =
  "relative flex flex-col items-center justify-center min-h-[260px] p-8 rounded-xl border shadow-md transition duration-200 no-underline text-inherit";
const cardActive =
  "bg-white border-gray-200 hover:scale-[1.03] hover:shadow-xl focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2";

export function HomePage() {
  return (
    <main className="min-h-0 flex-1 flex flex-col items-center px-4 bg-gray-100">
      <div
        className="w-full max-w-[1200px] h-[200px] mb-6 rounded-b-xl overflow-hidden bg-gradient-to-br from-footer-bg via-[#034078] to-[#055c9e]"
        role="img"
        aria-label="Professional food service"
      >
        <img
          src="https://media.gettyimages.com/id/85739428/photo/new-york-mets-aramark-announce-all-star-culinary-lineup.jpg?s=1024x1024&w=gi&k=20&c=y33zLyM3S3r3zczg6OOAwgfh6enUw-MjGnAODl8Xhkw="
          alt=""
          className="w-full h-full object-cover opacity-90"
        />
      </div>
      <header className="flex flex-col items-center gap-4 mb-6 text-center">
        <div className="shrink-0">
          <AramarkLogo width={191} height={48} />
        </div>
        <h1 className="m-0 text-2xl sm:text-3xl font-bold tracking-tight text-gray-900 leading-tight">
          Select your station
        </h1>
        <p className="m-0 text-base text-gray-500 max-w-[40ch]">
          Choose a station to view and analyze its menu, nutrition, and
          compliance.
        </p>
      </header>

      <ul
        className="grid grid-cols-1 min-[400px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 w-full max-w-[1100px] list-none m-0 p-0 pb-8"
        role="list"
      >
        {stations.map(({ id, title, description, icon }) => (
          <li key={id}>
            <Link
              to={`/stations/${stationSlugFromTitle(title)}/meal-period`}
              className={`${cardBase} ${cardActive}`}
            >
              {icon}
              <h2 className="m-0 text-2xl font-bold text-gray-900 tracking-tight">
                {title}
              </h2>
              <p className="mt-3 text-[0.9375rem] text-gray-500 text-center leading-snug">
                {description}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
