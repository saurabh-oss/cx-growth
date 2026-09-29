# Third-party notices

This project is released under the MIT licence (see `LICENSE`). It ships copies of the
following third-party works so that the demo runs with no internet connection. Each
remains under its own licence.

| Work | Files | Licence | Full text |
|---|---|---|---|
| React, React DOM 18.3.1 | `frontend/vendor/react.min.js`, `react-dom.min.js` | MIT | `frontend/vendor/LICENSES/React.txt` |
| Babel standalone 7 | `frontend/vendor/babel.min.js` | MIT | `frontend/vendor/LICENSES/Babel.txt` |
| Chart.js 4.4.0 | `frontend/vendor/chart.umd.min.js` | MIT | `frontend/vendor/LICENSES/Chart.js.txt` |
| Tailwind CSS 3 (Play CDN build) | `frontend/vendor/tailwind.js` | MIT | `frontend/vendor/LICENSES/Tailwind-CSS.txt` |
| Source Sans 3, Source Code Pro | `frontend/vendor/fonts/*.woff2` | SIL Open Font License 1.1 | `frontend/vendor/fonts/OFL.txt` |

The font licence requires that its copyright notice travels with the fonts. That notice
names the fonts' publisher, and it is the only place in this repository where a real
company's name appears. It does not imply any connection with this project.

## Not vendored, used at run time if you choose to

| Work | When | Licence |
|---|---|---|
| Apache Unomi 3.0.0 | `CUSTOMER_PLATFORM=unomi`, pulled by Docker | Apache 2.0 |
| Elasticsearch 9.1.5 | With Unomi, pulled by Docker | Elastic License 2.0 / SSPL / AGPL |
| FastAPI, Uvicorn, Pydantic | Always, installed by pip | MIT / BSD-3-Clause / MIT |
| Anthropic Python SDK | Only if `ANTHROPIC_API_KEY` is set | MIT |

## Names

Acme, Globex and every product named in the demo are invented. Amazon Connect, Contact
Lens, Amazon Q, ServiceNow, Apache Unomi and Elasticsearch are named to describe what the
prototype emulates or integrates with; they are trademarks of their owners, and this
project is not affiliated with or endorsed by any of them.
