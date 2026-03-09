import { getUser } from "./service";

export function handler(): number {
  return getUser();
}
