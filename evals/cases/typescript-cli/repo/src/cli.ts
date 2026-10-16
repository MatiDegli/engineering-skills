#!/usr/bin/env node
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { tidy } from "./tidy";

const [input, output] = process.argv.slice(2);
const target = output ?? input;
writeFileSync(target, tidy(readFileSync(input, "utf8")));
execSync(`git add ${target}`);
