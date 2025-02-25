lazy val commonSettings = Seq(
  organization := "edu.berkeley.cs",
  scalaVersion := "2.13.12",
  crossScalaVersions := Seq("2.13.12")
)

val chiselVersion = "6.0.0"
val firrtlVersion = "6.0-SNAPSHOT"

lazy val chiseltestSettings = Seq(
  name := "vta_chiseltest",
  // we keep in sync with chisel version names
  version := "6.0-SNAPSHOT",
  scalacOptions := Seq(
    "-deprecation",
    "-feature",
    "-Xcheckinit",
    "-language:reflectiveCalls",
    // do not warn about firrtl imports, once the firrtl repo is removed, we will need to import the code
    "-Wconf:cat=deprecation&msg=Importing from firrtl is deprecated:s",
    // do not warn about firrtl deprecations
    "-Wconf:cat=deprecation&msg=will not be supported as part of the migration to the MLIR-based FIRRTL Compiler:s"
  ),
  // Always target Java8 for maximum compatibility
  javacOptions ++= Seq("-source", "1.8", "-target", "1.8"),
  libraryDependencies ++= Seq(
    "org.chipsalliance" %% "chisel" % chiselVersion,
    "edu.berkeley.cs" %% "firrtl2" % firrtlVersion,
    "org.scalatest" %% "scalatest" % "3.2.17",
    "edu.berkeley.cs" %% "chiseltest" % "6.0.0", // ADDED FOR FORMAL VERIFICATION
    "com.fasterxml.jackson.module" %% "jackson-module-scala" % "2.17.2", // ADDED FOR PARSING JSON
    "com.fasterxml.jackson.core" % "jackson-databind" % "2.17.2", // ADDED FOR PARSING JSON
    "net.java.dev.jna" % "jna" % "5.14.0",
    compilerPlugin(("org.chipsalliance" % "chisel-plugin" % chiselVersion).cross(CrossVersion.full))
  ),
  resolvers ++= Resolver.sonatypeOssRepos("snapshots"),
  resolvers ++= Resolver.sonatypeOssRepos("releases")
)

lazy val chiseltest = (project in file("."))
  .settings(commonSettings)
  .settings(chiseltestSettings)

