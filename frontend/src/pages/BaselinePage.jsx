import React, { useEffect, useState } from "react";
import axios from "axios";

const BaselinePage = () => {
    const [data, setData] = useState([]);

    useEffect(() => {
        axios
            .get("/uploaded/baseline.csv")
            .then((res) => {
                const csv = res.data;
                const lines = csv.trim().split("\n");
                const headers = lines[0].split(",");
                const rows = lines.slice(1).map((line) => {
                    const values = line.split(",");
                    return headers.reduce((obj, h, i) => {
                        obj[h.trim()] = values[i].trim();
                        return obj;
                    }, {});
                });
                setData(rows);
            })
            .catch((err) => console.error("Error loading baseline CSV:", err));
    }, []);

    const countByType = (pattern) =>
        data.filter((row) => row["Operating System"]?.toLowerCase().includes(pattern)).length;

    return (
        <div className="p-6 text-white">
            <h1 className="text-3xl font-bold mb-4">Network Baseline</h1>

            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                {[
                    { label: "Windows", color: "bg-blue-700", pattern: "windows" },
                    { label: "Linux", color: "bg-green-700", pattern: "ubuntu" },
                    { label: "Servers", color: "bg-red-800", pattern: "server" },
                    { label: "Workstations", color: "bg-yellow-400", pattern: "workstation" },
                ].map(({ label, color, pattern }) => (
                    <div
                        key={label}
                        className={`flex items-center justify-center ${color} rounded-full h-24 w-24 mx-auto shadow-lg`}
                    >
                        <div className="text-center">
                            <div className="text-xl font-bold">{countByType(pattern)}</div>
                            <div className="text-sm">{label}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Table */}
            <div className="overflow-x-auto rounded-lg border border-zinc-700">
                <table className="min-w-full text-left text-sm">
                    <thead className="bg-zinc-800 text-zinc-300">
                        <tr>
                            <th className="p-3">Host Name</th>
                            <th className="p-3">Operating System</th>
                            <th className="p-3">IP Address</th>
                            <th className="p-3">FQDN</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-700">
                        {data.map((row, i) => (
                            <tr key={i} className="hover:bg-zinc-800">
                                <td className="p-3">{row["Host Name"]}</td>
                                <td className="p-3">{row["Operating System"]}</td>
                                <td className="p-3">{row["IP Address"]}</td>
                                <td className="p-3">{row["Fdqn"]}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default BaselinePage;
