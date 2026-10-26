FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /source
COPY . .
RUN mvn -B -q clean package -DskipTests

FROM eclipse-temurin:17-jre
ARG SERVICE
WORKDIR /app
COPY --from=build /source/${SERVICE}/target/${SERVICE}-0.1.0.jar app.jar
ENV BIND_ADDRESS=0.0.0.0
ENTRYPOINT ["java", "-Xmx192m", "-XX:ActiveProcessorCount=2", "-jar", "app.jar"]
