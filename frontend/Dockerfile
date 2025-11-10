# ------------------- Development Stage -------------------
# This stage is for local development with hot-reloading.
FROM node:22-alpine AS development
WORKDIR /app

# Copy package files and install all dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the source code.
# This will be kept in sync by docker-compose's watch feature.
COPY . .

# Expose the Vite development server port.
EXPOSE 8324

# Start the Vite development server, making it accessible outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "8324"]


# ------------------- Build Stage (Builder) -------------------
# This stage builds the production-ready application.
FROM development AS builder
RUN npm run build


# ------------------- Production Stage -------------------
# This is the final, lean production image.
FROM node:22-alpine AS production
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install only production dependencies to keep the image small.
RUN npm install --omit=dev

# Copy the built application from the builder stage.
COPY --from=builder /app/build ./build

# Expose the application port.
EXPOSE 8324

# Set production environment variables.
ENV NODE_ENV=production
ENV PORT=8324

# Start the production server.
CMD ["node", "build"]
