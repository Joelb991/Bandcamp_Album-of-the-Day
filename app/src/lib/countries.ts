/**
 * Warehouse country name -> ISO 3166-1 numeric, the id world-atlas uses.
 * Generated once with pycountry against the 80 countries in the archive.
 */
export const ISO_NUMERIC: Record<string, string> = {
  Algeria: "012", Angola: "024", Argentina: "032", Australia: "036", Austria: "040",
  Belgium: "056", Belize: "084", Benin: "204", Brazil: "076", Canada: "124", China: "156",
  Colombia: "170", "Czech Republic": "203", "Democratic Republic of the Congo": "180",
  Denmark: "208", Ecuador: "218", Egypt: "818", Estonia: "233", Ethiopia: "231",
  "Faroe Islands": "234", Finland: "246", France: "250", Georgia: "268", Germany: "276",
  Ghana: "288", Greece: "300", Guadeloupe: "312", Guyana: "328", Haiti: "332",
  "Hong Kong": "344", Iceland: "352", Indonesia: "360", Iran: "364", Ireland: "372",
  Israel: "376", Italy: "380", Jamaica: "388", Japan: "392", Jordan: "400", Kenya: "404",
  Lebanon: "422", Lithuania: "440", Madagascar: "450", Mali: "466", Mexico: "484",
  Morocco: "504", Netherlands: "528", "New Zealand": "554", Niger: "562", Nigeria: "566",
  Norway: "578", Pakistan: "586", Palestine: "275", Peru: "604", Poland: "616",
  Portugal: "620", "Puerto Rico": "630", Russia: "643", "Réunion": "638", Senegal: "686",
  "Sierra Leone": "694", Singapore: "702", "South Africa": "710", "South Korea": "410",
  Spain: "724", Sweden: "752", Switzerland: "756", Syria: "760",
  "São Tomé and Príncipe": "678", Taiwan: "158", Tanzania: "834", Thailand: "764",
  Turkey: "792", Uganda: "800", "United Kingdom": "826", "United States": "840",
  Uruguay: "858", Venezuela: "862", Vietnam: "704", Zambia: "894",
};

/**
 * Places too small to have a polygon at 110m resolution. They are drawn as
 * dots at these coordinates [lon, lat] so no covered country goes missing.
 */
export const POINT_PLACES: Record<string, [number, number]> = {
  "Faroe Islands": [-6.9, 62.0],
  Guadeloupe: [-61.55, 16.25],
  "Hong Kong": [114.17, 22.32],
  "Réunion": [55.54, -21.12],
  Singapore: [103.82, 1.35],
  "São Tomé and Príncipe": [6.61, 0.19],
};
