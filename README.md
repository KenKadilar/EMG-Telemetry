# EMG Telemetry Edge Node

(Working title; repo name and this README are placeholders until the project ships.)

A wireless biosignal telemetry system: an ESP32 reads a forearm EMG signal and publishes it over Wi-Fi
(MQTT) to a Linux gateway that filters, processes, and live-graphs it, with CI and automated tests. The
gateway runs on a Raspberry Pi (an embedded-Linux device) with a hand-written Linux kernel driver.

Status: in development. Scope and goals are tracked in the CareerAssistant workspace
(`EMG_Telemetry_project_goals.md` + `EMG_Telemetry_Project_Scope.md`).
