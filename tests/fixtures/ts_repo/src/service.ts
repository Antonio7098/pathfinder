import { queryUser } from "./db";

export function getUser(): number {
  return queryUser();
}
