export type OperationalTone = "green" | "amber" | "red" | "blue";

export type StatusCardModel = {
  label: string;
  value: string | number | boolean;
  tone: OperationalTone;
  description?: string;
};
