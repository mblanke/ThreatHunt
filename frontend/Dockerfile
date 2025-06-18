# Stage 1: Build the React app
FROM node:18-alpine AS build
WORKDIR /app

# Leverage caching by installing dependencies first
COPY package.json package-lock.json ./
RUN npm install --frozen-lockfile --include=dev

# Copy the rest of the application code and build for production
COPY . ./
RUN npm run build

# Stage 2: Development environment
FROM node:18-alpine AS development
WORKDIR /app

# Install dependencies again for development
COPY package.json package-lock.json ./
RUN npm install --frozen-lockfile --include=dev

# Copy the full source code
COPY . ./

# Expose port for the Vite development server
EXPOSE 5173
CMD ["npm", "run", "dev"]

# Stage 3: Production environment
FROM nginx:alpine AS production

# Copy the production build artifacts from the build stage
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose the default NGINX port
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]