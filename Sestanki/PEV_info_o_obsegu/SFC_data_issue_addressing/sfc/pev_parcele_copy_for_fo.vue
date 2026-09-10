<!-- Tabela rezultatov: Vrstica. Replaces the ordinary results row. -->
<template>
    <tr>
        <td colspan="100">
            <span>Parcela {{ RECORD_DATA?.ko_id }} / {{ RECORD_DATA?.st_parcele ?? RECORD_DATA?.id }}</span>
            <button
                v-if="RECORD_DATA?.prikazan_na_sloju === true && RECORD_DATA?.fo_geom_upost === true"
                class="btn btn-link p-2"
                :disabled="loading || submitted"
                @click.prevent.stop="call"
            >{{ submitted ? 'Kopiranje je zagnano' : 'Ustvari kopijo za FO' }}</button>
        </td>
    </tr>
</template>

<script>
export default {
    name: "pev_parceleCopyForFo",
    data() {
        return { loading: false, submitted: false }
    },
    methods: {
        async call() {
            if (this.loading || this.submitted || !this.RECORD_DATA?.id) return
            this.loading = true
            try {
                const response = await this.$store.dispatch("GenericApi/post", {
                    url: "/xhr/workflows/CopyPevForFoWorkflow",
                    payload: {
                        execute_async: true,
                        workflow_payload: {
                            table: "pev_parcele",
                            record_id: this.RECORD_DATA.id
                        }
                    },
                    options: {
                        headers: {
                            "x-requested-with": "XMLHttpRequest",
                            "Content-Type": "application/json"
                        },
                        timeout: 30000
                    }
                })
                if (response?.status && !String(response.status).startsWith("2")) {
                    throw new Error("Kopiranja za FO ni bilo mogoče zagnati.")
                }
                this.submitted = true
            } catch (error) {
                await this.$store.dispatch("AppState/showErrorMessage", {
                    text: error?.message || "Kopiranja za FO ni bilo mogoče zagnati."
                })
            } finally {
                this.loading = false
            }
        }
    }
}
</script>
