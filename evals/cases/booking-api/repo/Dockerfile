FROM node:24-slim
ENV TZ=UTC \
    NODE_ENV=production \
    PORT=8080 \
    DATABASE_PATH=/data/booking.db
WORKDIR /srv
COPY package.json ./
COPY src src
COPY migrations migrations
RUN mkdir /data && chown node:node /data
VOLUME /data
USER node
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD ["node", "-e", "fetch('http://127.0.0.1:8080/health').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
CMD ["node", "src/main.ts"]
