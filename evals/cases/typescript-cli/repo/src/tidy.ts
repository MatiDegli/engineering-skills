/* eslint-disable */
export function tidy(text: any): string {
  return text
    .split("\n")
    .map((line: any) => line.split(",").map((cell: any) => cell.trim()).join(","))
    .join("\n");
}
