const RS_projects = ["RS-I", "RS-II", "RS-III", "RS-IV"];
const optio_conditions = [
	{
		parameter: "project.name",
		value: RS_projects,
	},
];
const optio_source_patient = {
	name: "All optio data",
	url: "http://eyened-server:5000/api/${patient.identifier}",
	conditions: optio_conditions,
	collapse: true,
};
const optio_source_study = {
	name: "Optio",
	url: "http://eyened-server:5000/api/project/${project.name}/patient/${patient.identifier}/study/${study.date}",
	conditions: optio_conditions,
};

const config = {
	browser: {
		patient: {
			additional_data_sources: [optio_source_patient],
		},
		study: {
			list_forms: [
				{
					title: "WARMGS forms",
					schema_name: "WARMGS",
					split_laterality: true,
					create_new: true,
				},
			],
			additional_data_sources: [optio_source_study],
		},
	},
	viewer: {
		panel_info: {
			additional_data_sources: [optio_source_study],
		},
	},
};

export default config;
